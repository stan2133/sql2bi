# Step 3 Reference: MCP Capability Discovery, Data Sampling, And Data Map

## Purpose
Verify that data is analyzable before heavy SQL.
Build a minimal, auditable data map with explicit capability and risk boundaries.

## Scope
This step is for metadata discovery, sampling, and join-path validation only.
Do not run full-scale analytical queries here.

## Input
- `decision_card` from Step 1
- `business_semantic_contract` from Step 2

## Procedure
1. Discover MCP capabilities.
2. Identify candidate tables and join keys.
3. Execute sampling queries.
4. Validate data quality and join safety.
5. Produce `data_map_contract`.

## 1) MCP Capability Discovery
Record the exact tool/resource names in this environment:
- metadata list tools (db/schema/table/column)
- query execution tool
- optional explain/plan tool

If capability is missing, continue with best-effort mode and mark risk.

## 2) Candidate Table And Join Path Discovery
Select:
- 1 primary fact table
- 1-3 required dimension tables

For each join, record:
- join columns
- expected cardinality (`1:1`, `1:N`, `N:1`, `N:N`)
- expected null behavior

## 3) Data Sampling Protocol (Required)
Sampling is mandatory before full analysis.

Run three sampling types:
1. Random sample:
   - objective: fast semantic inspection
   - method: random row subset or hash-based sample
2. Stratified sample:
   - objective: ensure major segments are represented
   - method: sample by key dimensions (`region`, `channel`, `product`, etc.)
3. Recent-window sample:
   - objective: validate freshness and recent behavior
   - method: sample last N days according to decision window grain

Optional:
4. Edge-case sample:
   - objective: inspect high-risk tails (high value transactions, rare categories)

## Sampling Guardrails
- Keep each sampling query bounded (`LIMIT`, bounded date window).
- Prefer deterministic sampling for reproducibility (hash-based where possible).
- Use stable seed/logic for repeated runs.
- Record sample filters and sample size.

## Sampling SQL Patterns
Random/hash sample pattern:
```sql
SELECT
  *
FROM fact_table
WHERE event_time >= :start_time
  AND event_time < :end_time
  AND MOD(ABS(HASH(CAST(primary_id AS STRING))), 100) < :sample_pct
LIMIT :sample_limit;
```

Stratified sample pattern:
```sql
WITH base AS (
  SELECT
    region,
    channel,
    primary_id,
    event_time,
    metric_value
  FROM fact_table
  WHERE event_time >= :start_time
    AND event_time < :end_time
),
ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY region, channel
      ORDER BY event_time DESC
    ) AS rn
  FROM base
)
SELECT *
FROM ranked
WHERE rn <= :rows_per_segment;
```

Recent-window sample pattern:
```sql
SELECT
  *
FROM fact_table
WHERE event_time >= DATE_SUB(:end_time, INTERVAL :recent_days DAY)
  AND event_time < :end_time
ORDER BY event_time DESC
LIMIT :sample_limit;
```

## 4) DDL Restriction Policy (Required)
Default mode is strict read-only.

Hard denylist for Step 3:
- `CREATE`
- `ALTER`
- `DROP`
- `TRUNCATE`
- `RENAME`
- `OPTIMIZE`
- any `INSERT`, `UPDATE`, `DELETE`, `MERGE`

Allowed:
- metadata introspection statements
- `SELECT`
- explain/plan statements (if available)

If a non-read-only statement is requested:
- do not execute
- return `ddl_blocked` with reason
- ask for explicit policy override only outside Step 3 workflow

## 5) Data Quality And Join Safety Checks
Minimum checks:
1. key column null-rate
2. duplicate-rate on expected unique keys
3. date coverage and freshness
4. pre-join vs post-join row-count drift
5. dimension coverage (unknown/other bucket share)

Fail conditions:
- freshness breach beyond SLA
- join drift exceeds tolerance
- required key missing at high rate

## Output Template
```json
{
  "data_map_contract": {
    "capability_map": {
      "metadata_tools": [],
      "query_tool": "",
      "explain_tool": "",
      "notes": []
    },
    "table_roles": {
      "fact_table": "",
      "dimension_tables": []
    },
    "join_plan": [
      {
        "left_table": "",
        "right_table": "",
        "join_keys": [],
        "expected_cardinality": "1:1|1:N|N:1|N:N",
        "risk_note": ""
      }
    ],
    "sampling_summary": {
      "random_sample": {"rows": 0, "filters": []},
      "stratified_sample": {"rows": 0, "strata": []},
      "recent_window_sample": {"rows": 0, "window": ""}
    },
    "read_only_policy": {
      "ddl_blocked": true,
      "blocked_keywords": [],
      "violations": []
    },
    "quality_flags": [],
    "release_gate": "PASS|WARN|FAIL",
    "blocked_reasons": []
  }
}
```

## Release Gate Rule
- `PASS`: move to Step 4 directly.
- `WARN`: continue with confidence cap and explicit caveats.
- `FAIL`: stop and request data or policy remediation.
