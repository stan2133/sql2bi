# Step 4 Reference: Hypothesis Tree And Test Plan

## Purpose
Turn business intuition into falsifiable hypotheses and an executable validation plan.
This step produces planning artifacts only; heavy SQL execution happens in Step 5.

## Inputs
- `decision_card` (Step 1)
- `business_semantic_contract` (Step 2)
- `data_map_contract` (Step 3)

## Output
- `hypothesis_test_plan`
- `release_gate`: `PASS|WARN|FAIL`

## Procedure
1. Decompose target KPI into driver tree.
2. Seed candidate hypotheses from selected domain packs.
3. Define falsifiable hypothesis nodes.
4. Attach query triad for each hypothesis.
5. Score and rank hypotheses.
6. Apply gate checks and publish plan.

## 1) KPI Decomposition Rules
Use multiplicative or additive decomposition that matches metric semantics.

Examples:
- `gmv = traffic * conversion_rate * aov`
- `revenue = active_users * arpu`
- `attrition_impact = attrition_rate * avg_productivity_loss`
- `gross_margin = 1 - (cogs / revenue)`

Rules:
- each driver must map to observable fields
- each driver must be measurable at the chosen grain
- decomposition must preserve reconciliation with parent KPI

## 2) Domain Hypothesis Seeding
Load seed ideas from the selected Step 2 domain packs and convert to explicit hypotheses.

Seed structure:
- `domain`
- `driver`
- `risk_signal`
- `expected_direction`

Cross-domain examples:
- Growth + NPS:
  - activation drop due to onboarding friction and support wait-time increase
- Sales + HR:
  - quota attainment decline due to rep ramp-time increase and staffing gaps
- Manufacturing + Supply Chain:
  - OTIF decline due to line downtime and supplier delay overlap
- Fraud + Finance:
  - revenue growth with worsening net margin due to rising fraud losses

## 3) Hypothesis Node Schema
Each hypothesis must be falsifiable and contain:
- `hypothesis_id`
- `statement`
- `type`: `correlation|causal_candidate`
- `expected_direction`: `up|down|mixed`
- `target_driver`
- `segment_scope`
- `pass_criterion`
- `fail_criterion`
- `dependencies`

Invalid hypothesis example:
- "Users are unhappy so revenue dropped."

Valid hypothesis example:
- "In region=US, onboarding completion dropped by >=3pp week-over-week, explaining >=25% of activation decline."

## 4) Query Triad Requirement
Every hypothesis needs three query classes:
1. `evidence_query`
   - tests whether primary signal exists
2. `counter_query`
   - challenges alternative explanations
3. `reconcile_query`
   - verifies driver contribution reconciles to top-line movement

Minimum requirement:
- no hypothesis can be ranked `P0` without all three query classes defined.

## 5) Prioritization Model
Score each hypothesis:
- `impact`: business value if true (1-5)
- `plausibility`: prior likelihood from history/domain knowledge (1-5)
- `actionability`: ability to act within decision horizon (1-5)
- `cost`: analysis effort/data complexity (1-5, higher is costlier)

Formula:
- `priority_score = (impact * plausibility * actionability) / cost`

Priority buckets:
- `P0`: score >= 12
- `P1`: score >= 7 and < 12
- `P2`: score < 7

## 6) Gate Checks
Before publishing Step 4 output, verify:
1. each hypothesis maps to at least one measurable driver
2. each hypothesis has query triad defined
3. criteria are numeric or logically testable
4. plan respects Step 2 semantic contract
5. plan can run on Step 3 data map without forbidden joins

Gate policy:
- `PASS`: proceed to Step 5
- `WARN`: proceed with confidence cap and listed caveats
- `FAIL`: block and return missing prerequisites

## Causality Guardrail
- Default all hypotheses to `correlation`.
- Use `causal_candidate` only when there is:
  - experiment/quasi-experiment evidence, or
  - strong temporal and segment controls
- Final report must not phrase `correlation` hypotheses as causal claims.

## Output Template
```json
{
  "hypothesis_test_plan": {
    "kpi_decomposition": {
      "target_kpi": "",
      "formula": "",
      "drivers": []
    },
    "hypotheses": [
      {
        "hypothesis_id": "H1",
        "statement": "",
        "type": "correlation|causal_candidate",
        "expected_direction": "up|down|mixed",
        "target_driver": "",
        "segment_scope": [],
        "pass_criterion": "",
        "fail_criterion": "",
        "queries": {
          "evidence_query_id": "",
          "counter_query_id": "",
          "reconcile_query_id": ""
        },
        "priority_inputs": {
          "impact": 1,
          "plausibility": 1,
          "actionability": 1,
          "cost": 1
        },
        "priority_score": 1.0,
        "priority_bucket": "P0|P1|P2",
        "dependencies": [],
        "risks": []
      }
    ],
    "release_gate": "PASS|WARN|FAIL",
    "blocked_reasons": []
  }
}
```

## Example
```json
{
  "hypothesis_test_plan": {
    "kpi_decomposition": {
      "target_kpi": "gmv",
      "formula": "traffic * conversion_rate * aov",
      "drivers": ["traffic", "conversion_rate", "aov"]
    },
    "hypotheses": [
      {
        "hypothesis_id": "H1",
        "statement": "Paid social traffic fell >=15% WoW and explains >=40% of GMV decline.",
        "type": "correlation",
        "expected_direction": "down",
        "target_driver": "traffic",
        "segment_scope": ["channel=paid_social", "region=US"],
        "pass_criterion": "traffic_wow_change <= -0.15 AND contribution >= 0.40",
        "fail_criterion": "traffic_wow_change > -0.05",
        "queries": {
          "evidence_query_id": "Q_H1_EVIDENCE",
          "counter_query_id": "Q_H1_COUNTER",
          "reconcile_query_id": "Q_H1_RECON"
        },
        "priority_inputs": {
          "impact": 5,
          "plausibility": 4,
          "actionability": 4,
          "cost": 2
        },
        "priority_score": 40.0,
        "priority_bucket": "P0",
        "dependencies": ["metric_definition_confirmed"],
        "risks": ["campaign attribution lag 24h"]
      }
    ],
    "release_gate": "PASS",
    "blocked_reasons": []
  }
}
```
