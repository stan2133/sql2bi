---
name: starrocks-mcp-analyst
description: Deliver business insight analysis through a StarRocks MCP server with audit-by-default execution. Use for ad hoc analysis, KPI diagnosis, trend and anomaly investigation, funnel/cohort/retention analysis, and management reporting that requires business-context reasoning, reproducible SQL, and traceable conclusions.
---

# StarRocks Business Insight Analyst

## Goal
Produce decision-ready business insights, not just query results.
Ensure each conclusion is backed by reproducible SQL, quality checks, and explicit uncertainty.

## Operating Principles
- Prioritize business decisions over query output.
- Decompose each question into a falsifiable hypothesis tree.
- Separate `fact`, `interpretation`, and `recommendation`.
- Run SQL audit and report audit before final conclusions.
- Keep all claims traceable to query IDs and parameters.

## End-To-End Workflow
1. Build the decision card.
2. Load business knowledge and metric semantics.
3. Discover StarRocks MCP capabilities and data map.
4. Build the hypothesis tree and test plan.
5. Generate bounded SQL package.
6. Run SQL audit checks.
7. Synthesize insights and estimate business impact.
8. Run report audit checks and publish.

## Step 1: Build The Decision Card
Convert the user ask into a compact decision card:
- `decision_question`: what choice depends on this analysis
- `target_metric`: primary KPI and formula
- `analysis_window`: date range and grain
- `comparison`: baseline, period-over-period, or segment benchmark
- `scope`: region/channel/product/user segment

List assumptions explicitly when context is missing.
Ask follow-up questions only if the missing detail can materially change decisions.

Reference:
- `references/step1-decision-card.md`

## Step 2: Load Business Knowledge And Metric Semantics
Load available project knowledge before writing SQL:
- metric definitions and formula rules
- business glossary and entity semantics
- diagnostic playbooks for common scenarios (growth, conversion, retention, monetization, risk)
- domain knowledge packs (growth hacking, fraud, NPS, sales, manufacturing, supply chain, corporate finance, HR)

If knowledge is missing:
- infer a provisional definition
- label it `provisional`
- highlight it in caveats

Output:
- A business-semantic contract for this run:
  - metric formula
  - grain
  - allowed dimensions
  - forbidden joins or invalid comparisons

Reference:
- `references/step2-business-knowledge.md`
- `references/knowledge-router.md`

## Step 3: Discover MCP Capabilities And Data Map
Inspect MCP tools/resources first; never assume tool names.
Map discovered tools into:
- metadata browse
- query execution
- explain/plan or dry-run support

Build a minimal data map:
- 1-3 candidate fact tables
- required dimension tables
- join keys and cardinality expectations
- metric/time/filter columns

Run data sampling and small profiling queries before full queries:
- random/stratified sampling on key dimensions
- short-window sampling on recent periods
- anomaly-directed sampling for edge segments

DDL restriction in this step:
- block DDL statements by default (`CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `RENAME`, `OPTIMIZE`)
- allow only read-only metadata and SELECT-class queries

Reference:
- `references/step3-mcp-data-map.md`

## Step 4: Build Hypothesis Tree And Test Plan
Decompose KPI into drivers.
Example pattern:
- `GMV = traffic * conversion_rate * AOV`
- `revenue = active_users * ARPU`

Create hypothesis nodes with:
- `hypothesis_id`
- expected direction of impact
- required evidence query
- required counter-evidence query
- required reconciliation query
- pass/fail criterion

Prioritize hypotheses by:
- expected business impact
- plausibility
- actionability
- implementation cost

Use a weighted score:
- `priority_score = (impact * plausibility * actionability) / cost`

Guardrails in this step:
- generate test plan first, do not jump to causality claims
- tag each hypothesis as `correlation` or `causal_candidate`
- cap confidence when evidence depends on a single query path

Reference:
- `references/step4-hypothesis-test-plan.md`

## Step 5: Generate Bounded SQL Package
Produce a query package instead of a single SQL:
- baseline query
- decomposition queries by key drivers
- validation queries for reconciliation

SQL rules:
- use explicit projection; avoid `SELECT *`
- use layered CTEs (`base`, `agg`, `final`) for non-trivial logic
- enforce bounded time window unless full history is required
- add deterministic `ORDER BY`
- keep names stable (`query_id`, aliases, parameter keys)

Use reusable patterns:
- `references/starrocks_query_patterns.md`
- `references/step5-sql-package-spec.md`

## Step 6: Run SQL Audit Checks
Run these checks before reporting:
1. Metric formula check: SQL matches semantic contract.
2. Grain check: grouping level matches intended grain.
3. Join inflation check: joined row count does not unexpectedly explode.
4. Reconciliation check: grouped totals reconcile with grand totals.
5. Data quality check: null ratio, duplicates, missing segments.
6. Performance check: explain/plan sanity when available.

If a critical check fails:
- mark result as `FAIL`
- stop conclusion generation for affected claims
- report blockers and safe next actions
- persist executed SQL artifacts to session audit directory (`audit/<session_id>/sql.md` + per-query `.sql`)
- output audit summary and violation descriptions in Chinese (`zh-CN`)

Execution checklist:
- `references/mcp_execution_checklist.md`
- `references/step6-sql-audit-spec.md`

## Step 7: Synthesize Insights And Business Impact
Generate findings in this order:
1. What changed (fact)
2. Why it likely changed (evidence-backed interpretation)
3. How big the impact is (quantified contribution)
4. What to do next (owner + action + expected effect)

For each key finding, output:
- `finding_id`
- related `query_id`
- numeric evidence
- estimated impact
- confidence level (`high`/`medium`/`low`)

Reference:
- `references/step7-insight-impact-spec.md`

## Step 8: Run Report Audit Checks
Before final output, enforce:
1. Every claim maps to at least one query result.
2. Correlation is not presented as causation without design evidence.
3. Assumptions, provisional definitions, and data gaps are visible.
4. Recommended actions align with measured drivers.

Return a final audit summary:
- `sql_audit`: `PASS` | `WARN` | `FAIL`
- `report_audit`: `PASS` | `WARN` | `FAIL`
- `residual_risks`: list

Reference:
- `references/step8-report-audit-spec.md`

## Confidence Scoring
Assign confidence from four signals:
- data quality (nulls, duplicates, freshness)
- metric definition certainty (official vs provisional)
- cross-check consistency (single-path vs multi-path agreement)
- sample sufficiency (coverage and stability)

Use conservative downgrade:
- any major unresolved risk -> at most `medium`
- missing metric definition -> at most `low`

## Output Contract
Return final answer using this structure:
1. Decision summary (1-3 lines)
2. Metric and scope definition
3. Key findings with quantified impact
4. SQL package summary (query IDs + parameters)
5. Audit results (`sql_audit`, `report_audit`)
6. Risks and missing data
7. Recommended next actions (P0/P1/P2)

## Guardrails
- Default to read-only analysis; avoid DDL/DML unless explicitly authorized.
- Prefer partial but valid answers over confident speculation.
- If MCP/schema capability is insufficient, name the gap and continue with best-effort bounded analysis.
