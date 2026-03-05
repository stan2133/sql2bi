# Step 5 Reference: Bounded SQL Package Specification

## Purpose
Generate an executable SQL package from the Step 4 hypothesis plan.
Ensure every query is bounded, traceable, read-only, and auditable.

## Inputs
- `decision_card` (Step 1)
- `business_semantic_contract` (Step 2)
- `data_map_contract` (Step 3)
- `hypothesis_test_plan` (Step 4)

## Output
- `sql_package` with stable query IDs, parameter contract, and execution metadata.
- session-aware audit artifact plan for Step 6 persistence.

## SQL Package Components
A valid package contains these query groups:
1. `baseline_queries`
   - top-line KPI and core trend
2. `decomposition_queries`
   - KPI driver breakdown by key dimensions
3. `hypothesis_queries`
   - evidence queries per hypothesis
4. `counter_queries`
   - alternative explanation checks per hypothesis
5. `reconcile_queries`
   - total vs grouped sum and cross-path reconciliation
6. `quality_queries` (optional but recommended)
   - null ratio, duplicate checks, date coverage checks

## Query ID Convention
Use deterministic IDs:
- `Q_BASE_*` for baseline
- `Q_DEC_*` for decomposition
- `Q_H{n}_EVIDENCE`
- `Q_H{n}_COUNTER`
- `Q_H{n}_RECON`
- `Q_QC_*` for quality checks

Rules:
- IDs must be unique in a run.
- IDs should be stable across reruns with same logic.
- Every finding in report must reference query IDs.

## Parameter Contract
Each query must declare explicit parameters:
- `name`
- `type` (`date`, `datetime`, `string`, `int`, `float`, `bool`, `array<string>`, etc.)
- `required`
- `default` (if optional)
- `description`

Required global parameters:
- `start_date` or `start_time`
- `end_date` or `end_time`
- `timezone`
- `session_id` (required for audit artifact paths)

## SQL Construction Rules
1. Read-only only:
   - allow `SELECT` and explain/plan only
   - deny DDL/DML (`CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `RENAME`, `OPTIMIZE`, `INSERT`, `UPDATE`, `DELETE`, `MERGE`)
2. Bounded execution:
   - bounded time window is mandatory unless explicitly approved
   - exploratory queries require `LIMIT`
3. Explicit schema:
   - no `SELECT *`
   - explicit join keys and join type
4. Layered CTEs:
   - `base` -> `agg` -> `final` for non-trivial logic
5. Deterministic output:
   - include `ORDER BY` when row order matters
6. Semantic consistency:
   - metric formula must match Step 2 semantic contract
   - grain must match decision card

## Execution Modes
Generate two modes for each query when needed:
- `preview`:
  - small date window and/or lower limits for fast validation
- `full`:
  - production window for final evidence

Both modes must share the same business logic; only boundedness parameters can differ.

## Cross-Query Reconciliation Rules
At least one reconciliation query must validate:
1. top-line metric equals sum across decomposition dimensions (within tolerance)
2. hypothesis contribution sum does not exceed total movement
3. segment totals plus residual equals global total

Tolerance recommendation:
- absolute tolerance: domain-specific minimum unit
- relative tolerance: default <= 1%

## Quality And Risk Annotation
Each query should include:
- `risk_level`: `low|medium|high`
- `risk_reason`
- `expected_runtime_class`: `fast|medium|heavy`
- `depends_on_queries`: list of query IDs

## Package Validation Checklist
Before handing to Step 6:
1. each `P0` hypothesis has evidence/counter/reconcile query IDs
2. every query is parameterized, no hardcoded sensitive constants
3. no forbidden SQL keyword appears
4. all tables/columns exist in Step 3 data map
5. query outputs include fields needed by Step 7 reporting
6. `session_id` is present for audit artifact generation

If validation fails:
- mark `sql_package_status = FAIL`
- return `blocked_reasons`

## Output Template
```json
{
  "sql_package": {
    "sql_package_status": "PASS|WARN|FAIL",
    "global_parameters": [
      {"name": "start_date", "type": "date", "required": true, "description": "analysis window start"},
      {"name": "end_date", "type": "date", "required": true, "description": "analysis window end"},
      {"name": "timezone", "type": "string", "required": true, "default": "UTC", "description": "timezone context"},
      {"name": "session_id", "type": "string", "required": true, "description": "session key for audit directory"}
    ],
    "queries": [
      {
        "query_id": "Q_BASE_KPI_TREND",
        "group": "baseline|decomposition|hypothesis|counter|reconcile|quality",
        "hypothesis_id": "",
        "sql": "",
        "parameters": [],
        "mode": "preview|full",
        "risk_level": "low|medium|high",
        "risk_reason": "",
        "expected_runtime_class": "fast|medium|heavy",
        "depends_on_queries": [],
        "output_columns": []
      }
    ],
    "validation_summary": {
      "forbidden_keyword_violations": [],
      "unmapped_columns": [],
      "missing_query_links": [],
      "blocked_reasons": []
    },
    "audit_artifact_plan": {
      "session_id": "",
      "sql_md_path": "audit/<session_id>/sql.md",
      "sql_dir_path": "audit/<session_id>/sql"
    }
  }
}
```

## Example Skeleton
```json
{
  "sql_package": {
    "sql_package_status": "PASS",
    "global_parameters": [
      {"name": "start_date", "type": "date", "required": true},
      {"name": "end_date", "type": "date", "required": true},
      {"name": "timezone", "type": "string", "required": true, "default": "UTC"},
      {"name": "session_id", "type": "string", "required": true}
    ],
    "queries": [
      {"query_id": "Q_BASE_GMV_TREND", "group": "baseline", "mode": "preview"},
      {"query_id": "Q_DEC_CHANNEL_GMV", "group": "decomposition", "mode": "preview"},
      {"query_id": "Q_H1_EVIDENCE", "group": "hypothesis", "hypothesis_id": "H1", "mode": "preview"},
      {"query_id": "Q_H1_COUNTER", "group": "counter", "hypothesis_id": "H1", "mode": "preview"},
      {"query_id": "Q_H1_RECON", "group": "reconcile", "hypothesis_id": "H1", "mode": "preview"}
    ],
    "validation_summary": {
      "forbidden_keyword_violations": [],
      "unmapped_columns": [],
      "missing_query_links": [],
      "blocked_reasons": []
    },
    "audit_artifact_plan": {
      "session_id": "session_20260305_001",
      "sql_md_path": "audit/session_20260305_001/sql.md",
      "sql_dir_path": "audit/session_20260305_001/sql"
    }
  }
}
```
