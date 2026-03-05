# Step 7 Reference: Insight Synthesis And Business Impact Specification

## Purpose
Convert audited SQL outputs into decision-ready findings, quantified impact, and prioritized actions.

## Inputs
- `decision_card` (Step 1)
- `business_semantic_contract` (Step 2)
- `hypothesis_test_plan` (Step 4)
- `sql_audit_report` (Step 6)
- session audit artifacts (`audit/<session_id>/sql.md`, per-query `.sql` files)
- executed query results

## Output
- `insight_package`
- finding-level confidence and action priority

## Entry Gate
Step 7 can publish final insights only when:
- Step 6 `sql_audit` is `PASS` or `WARN`
- every finding references at least one `PASS|WARN` query audit
- `audit/<session_id>/sql.md` is present and complete

Language alignment:
- keep insight report language consistent with audit package language
- default language is Chinese (`zh-CN`) unless explicitly overridden by user

If Step 6 is `FAIL`:
- publish partial verified facts only
- do not publish full driver explanation

## Synthesis Workflow
1. Extract top-line movement facts.
2. Map hypothesis outcomes to supporting evidence.
3. Compute contribution and impact ranges.
4. Generate recommendation candidates.
5. Rank actions by impact and execution feasibility.
6. Produce final narrative with explicit uncertainty.

## Finding Construction Rules
Each finding must include:
- `finding_id`
- `statement` (fact first, interpretation second)
- `supporting_query_ids`
- `key_numbers` (baseline, current, delta, delta_pct)
- `confidence_level` (`high|medium|low`)
- `confidence_reason`

Hard rules:
- no finding without numeric evidence
- no causal wording for `correlation` hypotheses
- include caveat when evidence relies on one path only

## Impact Quantification Model
For each finding, compute:
- `observed_delta`
- `explained_share` of top-line change
- `impact_value` in business unit (revenue, cost, time, risk loss)
- `impact_range` (`low_estimate`, `base_estimate`, `high_estimate`)

Default approach:
- base estimate from audited query outputs
- low/high estimates from tolerance and data risk adjustments

Contribution check:
- sum of driver contributions + residual should reconcile with top-line movement

## Domain-Specific Impact Hints
- Growth:
  - impact as incremental GMV, retained users, payback shift
- Fraud:
  - impact as avoided loss, false-positive conversion cost, net risk-adjusted margin
- NPS/CX:
  - impact as churn-risk change, ticket load change, recovery value
- Sales:
  - impact as forecast delta, quota attainment delta, cycle-time cost
- Manufacturing:
  - impact as output gain, scrap cost reduction, downtime loss recovery
- Supply Chain:
  - impact as service-level recovery value, stockout loss avoided, inventory holding cost
- Corporate Finance:
  - impact as margin delta, working-capital release, cash conversion improvement
- HR:
  - impact as attrition cost avoided, hiring efficiency gain, productivity uplift

## Confidence Scoring Rules
Use four signals:
1. data quality
2. semantic certainty
3. cross-query consistency
4. sample adequacy

Heuristic:
- `high`: all signals strong, no major unresolved risks
- `medium`: one moderate weakness or unresolved warning
- `low`: provisional definitions, limited sample, or unresolved high-risk issue

Force downgrade:
- any unresolved high-severity SQL warning -> max `medium`
- provisional metric definition -> max `low`

## Recommendation Generation Rules
For each major finding, generate actions with:
- `action_id`
- `owner_role`
- `action_statement`
- `expected_impact`
- `time_horizon` (`immediate|short_term|mid_term`)
- `dependencies`
- `priority` (`P0|P1|P2`)

Priority policy:
- `P0`: high impact + high urgency + feasible in current horizon
- `P1`: meaningful impact but medium urgency or higher dependency
- `P2`: exploratory or long-cycle action

## Narrative Contract
Present in fixed order:
1. decision summary
2. what changed
3. why it likely changed
4. business impact
5. recommended actions
6. risks and unknowns

Language policy:
- use precise numeric statements
- avoid overstating certainty
- separate fact and interpretation

## Output Template
```json
{
  "insight_package": {
    "decision_summary": "",
    "topline": {
      "metric": "",
      "baseline_value": 0,
      "current_value": 0,
      "delta_value": 0,
      "delta_pct": 0
    },
    "findings": [
      {
        "finding_id": "F1",
        "statement": "",
        "hypothesis_id": "",
        "supporting_query_ids": [],
        "key_numbers": {
          "baseline": 0,
          "current": 0,
          "delta": 0,
          "delta_pct": 0
        },
        "impact": {
          "unit": "",
          "value": 0,
          "range": {
            "low_estimate": 0,
            "base_estimate": 0,
            "high_estimate": 0
          },
          "explained_share": 0
        },
        "confidence_level": "high|medium|low",
        "confidence_reason": "",
        "caveats": []
      }
    ],
    "actions": [
      {
        "action_id": "A1",
        "related_finding_ids": [],
        "owner_role": "",
        "action_statement": "",
        "expected_impact": "",
        "time_horizon": "immediate|short_term|mid_term",
        "priority": "P0|P1|P2",
        "dependencies": []
      }
    ],
    "audit_artifacts": {
      "session_id": "",
      "sql_md_path": "audit/<session_id>/sql.md",
      "sql_dir_path": "audit/<session_id>/sql"
    },
    "residual_risks": [],
    "next_checks": []
  }
}
```

## Example
```json
{
  "insight_package": {
    "decision_summary": "US paid social budget should not be increased this cycle; channel mix quality declined.",
    "topline": {
      "metric": "gmv",
      "baseline_value": 12500000,
      "current_value": 10900000,
      "delta_value": -1600000,
      "delta_pct": -0.128
    },
    "findings": [
      {
        "finding_id": "F1",
        "statement": "Paid social traffic dropped 18% WoW and explains 44% of GMV decline in US new users.",
        "hypothesis_id": "H1",
        "supporting_query_ids": ["Q_H1_EVIDENCE", "Q_H1_RECON"],
        "key_numbers": {
          "baseline": 2100000,
          "current": 1720000,
          "delta": -380000,
          "delta_pct": -0.181
        },
        "impact": {
          "unit": "gmv_usd",
          "value": -704000,
          "range": {
            "low_estimate": -640000,
            "base_estimate": -704000,
            "high_estimate": -760000
          },
          "explained_share": 0.44
        },
        "confidence_level": "medium",
        "confidence_reason": "evidence and reconcile queries align; attribution lag remains",
        "caveats": ["24h campaign attribution lag"]
      }
    ],
    "actions": [
      {
        "action_id": "A1",
        "related_finding_ids": ["F1"],
        "owner_role": "growth_marketing_lead",
        "action_statement": "shift 20% budget from low-intent adsets to historically high-retention cohorts",
        "expected_impact": "recover 200k to 300k weekly GMV if traffic quality stabilizes",
        "time_horizon": "immediate",
        "priority": "P0",
        "dependencies": ["campaign ops update within 24h"]
      }
    ],
    "audit_artifacts": {
      "session_id": "session_20260305_001",
      "sql_md_path": "audit/session_20260305_001/sql.md",
      "sql_dir_path": "audit/session_20260305_001/sql"
    },
    "residual_risks": ["model-based attribution not fully backfilled"],
    "next_checks": ["re-evaluate lift after 7 days with finalized attribution"]
  }
}
```
