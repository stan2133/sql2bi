# MCP Execution Checklist For Analysis

## 1) Capability Discovery
- List available MCP tools/resources before first query.
- Record exact names for metadata, query, and optional explain tools.
- Verify one read-only call succeeds.

## 2) Metadata Validation
- Confirm table existence and schema freshness.
- Confirm metric/time/filter columns exist and types are compatible.
- Confirm join keys are semantically aligned.

## 3) Query Safety
- Start with narrow time range and small result set.
- Add explicit projection list instead of `SELECT *`.
- Add deterministic `ORDER BY` for sampled outputs.
- Avoid unbounded scans during exploration.
- In Step 3, enforce read-only mode and block DDL/DML statements.

## 4) Result Quality Checks
- Compare grand total vs grouped total (reconciliation).
- Check null ratio for key dimensions.
- Check duplicates on expected unique keys.
- Check whether filters accidentally exclude all rows.

## 5) Performance Checks
- Prefer explain/plan capability when available.
- Reduce heavy query cost with pre-aggregation CTEs.
- Re-run with larger range only after sample passes sanity checks.

## 6) Reporting Contract
- Include executed SQL text or query payload.
- Include parameter values (time window, filters, top_n).
- Separate observed facts from interpretation.
- List caveats and missing capabilities explicitly.
- Persist full executed SQL to `audit/<session_id>/sql.md` for human escalation.
- Write audit narrative content in Chinese (`zh-CN`) by default.
- Enforce fail-fast: if SQL cannot be persisted to disk, stop workflow and mark audit as `FAIL`.
