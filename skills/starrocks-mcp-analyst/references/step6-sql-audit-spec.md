# Step 6 Reference: SQL Audit Specification

## Purpose
Audit SQL correctness, consistency, data quality, and performance before any business conclusion is published.

## Inputs
- `sql_package` (Step 5)
- `business_semantic_contract` (Step 2)
- `data_map_contract` (Step 3)
- query execution outputs and metadata

## Output
- `sql_audit_report`
- `sql_audit`: `PASS|WARN|FAIL`
- session-based audit artifacts in `audit/<session_id>/`

## Language Requirement (Required)
Audit content is for human escalation and must be written in Chinese (`zh-CN`) by default:
- `sql_audit_report.summary`, violation messages, remediation hints, residual risks: Chinese
- `audit/<session_id>/sql.md` narrative sections and field labels: Chinese
- SQL text itself remains unchanged (SQL keywords and identifiers keep original form)

Only switch to another language when user explicitly requests it.

## Audit Procedure
1. Run static SQL policy checks.
2. Run semantic consistency checks.
3. Run execution/result integrity checks.
4. Run reconciliation checks.
5. Run performance checks.
6. Persist full executed SQL artifacts to session audit directory.
7. Aggregate severity and produce gate decision.

## SQL 落盘强制策略（Blocking）
落盘不是建议项，是强制项。

执行每条查询后，必须同步完成：
1. 写入 `audit/<session_id>/sql/<query_id>.sql`（完整 SQL）
2. 在 `audit/<session_id>/sql.md` 追加本次执行记录
3. 记录参数、耗时、行数、状态

若任一步骤失败：
- 当前查询标记 `FAIL`
- 生成 violation：`category=artifact`, `severity=critical`
- `sql_audit` 直接置为 `FAIL`
- 停止 Step 7 最终发布

## Session-Based Audit Directory (Required)
Audit outputs must be persisted by session, not ad hoc run folder.

Required structure:
```text
audit/
  <session_id>/
    sql.md
    sql/
      Q_BASE_*.sql
      Q_DEC_*.sql
      Q_H1_EVIDENCE.sql
      Q_H1_COUNTER.sql
      Q_H1_RECON.sql
    sql_audit_report.json
    query_results_summary.json
```

Rules:
- `session_id` must be stable for the full user session.
- Every executed query must have one `.sql` file under `audit/<session_id>/sql/`.
- `audit/<session_id>/sql.md` must list all executed query IDs and contain full SQL text.
- Keep one section per `query_id` with runtime, row count, parameter values, and execution status.
- If rerun happens in same session, append new execution block with timestamp.
- `sql.md` section titles, explanations, and risk notes must use Chinese.

## 1) Static SQL Policy Checks
Required checks per query:
- no forbidden DDL/DML keyword
- explicit projection (no `SELECT *`)
- bounded time filter present unless approved exception
- parameterized constants for key filters
- deterministic ordering where row order matters

Failure severity:
- forbidden keyword -> `critical`
- no bounded time -> `high`
- select star in core query -> `high`
- SQL artifact persistence failure -> `critical`

## 2) Semantic Consistency Checks
Validate query logic against Step 2 contract:
- metric formula equivalence
- numerator/denominator definition integrity
- analysis grain alignment
- timezone and attribution window alignment
- valid dimensions only (forbidden cuts blocked)

Failure severity:
- metric mismatch -> `critical`
- grain mismatch -> `high`
- timezone mismatch -> `high`

## 3) Execution And Result Integrity Checks
Minimum checks:
1. key columns null ratio
2. duplicates on expected unique keys
3. date coverage completeness
4. unexpected zero-row outputs
5. outlier spikes beyond configured thresholds

Recommendations:
- compare preview vs full mode direction consistency
- compare current results to historical baseline band

Failure severity:
- missing key columns or all-null key metric -> `critical`
- duplicate explosion -> `high`
- freshness breach -> `high`

## 4) Reconciliation Checks
Required reconciliation classes:
1. top-line vs grouped sum
2. segment sum + residual vs global total
3. hypothesis contribution sum vs total movement

Default tolerance:
- relative error <= 1%
- absolute tolerance domain-specific

Failure severity:
- reconciliation breach above tolerance -> `critical`

## 5) Performance Checks
If explain/plan is available, inspect:
- partition pruning presence
- major scan/aggregation cost signals
- large skew indicators on join keys

Also track runtime:
- `fast`: < 10s
- `medium`: 10s to 60s
- `heavy`: > 60s

Failure severity:
- query timeout in critical path -> `high`
- heavy runtime without fallback plan -> `medium`

## Severity Model
Severity levels:
- `critical`
- `high`
- `medium`
- `low`

Gate rules:
- any `critical` -> `FAIL`
- no critical and >=2 `high` -> `WARN`
- otherwise `PASS`

## Required Remediation Behavior
When `FAIL`:
- block Step 7 final insight publishing
- return only verified partial findings
- provide explicit remediation SQL/checklist
- if caused by persistence failure, require re-run with successful artifact writes

When `WARN`:
- publish with confidence cap
- include unresolved risk list

## Query-Level Audit Record Schema
Each query needs:
- `query_id`
- `check_results` by audit category
- `violations` with severity
- `status`: `PASS|WARN|FAIL`
- `remediation_hint`
- `artifact_path_sql`: path to persisted SQL file

## sql.md Requirements (Human Escalation Package)
`sql.md` is mandatory and intended for human review/escalation.

Each query section must include:
1. `query_id`
2. `hypothesis_id` (if any)
3. `status`
4. `runtime_ms`
5. `row_count`
6. `parameters` (effective values used)
7. `sql_file` path
8. full rendered SQL in code fence

Language rule:
- all explanatory text in Chinese
- keep raw SQL untouched

Template reference:
- `references/audit-sql-md-template.md`
- `references/sql-audit-persistence-summary.md`

## Output Template
```json
{
  "sql_audit_report": {
    "language": "zh-CN",
    "sql_audit": "PASS|WARN|FAIL",
    "summary": {
      "total_queries": 0,
      "pass_queries": 0,
      "warn_queries": 0,
      "fail_queries": 0,
      "persisted_queries": 0
    },
    "violations": [
      {
        "query_id": "",
        "category": "policy|semantic|integrity|reconcile|performance",
        "severity": "critical|high|medium|low",
        "message": "",
        "remediation_hint": ""
      }
    ],
    "query_audits": [
      {
        "query_id": "",
        "status": "PASS|WARN|FAIL",
        "artifact_path_sql": "audit/<session_id>/sql/<query_id>.sql",
        "check_results": {
          "policy": "PASS|WARN|FAIL",
          "semantic": "PASS|WARN|FAIL",
          "integrity": "PASS|WARN|FAIL",
          "reconcile": "PASS|WARN|FAIL",
          "performance": "PASS|WARN|FAIL",
          "persistence": "PASS|WARN|FAIL"
        },
        "violations": [],
        "remediation_hint": ""
      }
    ],
    "residual_risks": [],
    "artifacts": {
      "session_id": "",
      "sql_md_path": "audit/<session_id>/sql.md",
      "sql_dir_path": "audit/<session_id>/sql",
      "query_results_summary_path": "audit/<session_id>/query_results_summary.json"
    }
  }
}
```

## Example
```json
{
  "sql_audit_report": {
    "language": "zh-CN",
    "sql_audit": "WARN",
    "summary": {
      "total_queries": 8,
      "pass_queries": 6,
      "warn_queries": 2,
      "fail_queries": 0,
      "persisted_queries": 8
    },
    "violations": [
      {
        "query_id": "Q_H2_EVIDENCE",
        "category": "integrity",
        "severity": "high",
        "message": "duplicate ratio on order_id is 3.4%, above threshold 1%",
        "remediation_hint": "deduplicate by latest event_time per order_id before aggregation"
      }
    ],
    "query_audits": [
      {
        "query_id": "Q_BASE_GMV_TREND",
        "status": "PASS",
        "check_results": {
          "policy": "PASS",
          "semantic": "PASS",
          "integrity": "PASS",
          "reconcile": "PASS",
          "performance": "PASS"
        },
        "violations": [],
        "remediation_hint": ""
      }
    ],
    "residual_risks": ["campaign attribution lag may shift recent-day conversion metrics"]
  }
}
```
