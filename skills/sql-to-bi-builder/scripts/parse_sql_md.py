#!/usr/bin/env python3.11
"""Parse sql.md into a normalized query catalog JSON."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
META_RE = re.compile(r"^\s*-\s*([a-zA-Z0-9_\-]+)\s*:\s*(.+?)\s*$")
SQL_FENCE_START_RE = re.compile(r"^\s*```\s*sql\s*$", re.IGNORECASE)
FENCE_END_RE = re.compile(r"^\s*```\s*$")
KNOWN_META_KEYS = {"id", "title", "datasource", "refresh", "chart", "filters"}


def _split_pairs(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"[;,]", text) if p.strip()]


def _parse_dict_text(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for pair in _split_pairs(text):
        if ":" in pair:
            key, value = pair.split(":", 1)
        elif "=" in pair:
            key, value = pair.split("=", 1)
        else:
            continue
        key = key.strip()
        value = value.strip()
        if key:
            out[key] = value
    return out


def _parse_derived_metrics(value: str) -> List[Dict[str, Any]]:
    raw = value.strip()
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            out: List[Dict[str, Any]] = []
            for item in parsed:
                if isinstance(item, dict):
                    out.append(item)
                elif isinstance(item, str):
                    out.append({"name": item, "type": item})
            return out
    except json.JSONDecodeError:
        pass

    out = []
    for token in _split_pairs(raw):
        parts = [p.strip() for p in token.split(":")]
        if len(parts) >= 2:
            item = {"name": parts[0], "type": parts[1]}
            if len(parts) >= 3 and parts[2]:
                item["base_metric"] = parts[2]
            out.append(item)
        else:
            out.append({"name": token, "type": token})
    return out


def parse_semantic_override(meta: Dict[str, str]) -> Dict[str, Any]:
    override: Dict[str, Any] = {}

    raw = meta.get("semantic_override", "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                override.update(parsed)
        except json.JSONDecodeError:
            override.update(_parse_dict_text(raw))

    if meta.get("semantic_grain"):
        override["grain"] = meta["semantic_grain"].strip()
    if meta.get("semantic_time_field"):
        override["time_field"] = meta["semantic_time_field"].strip()
    if meta.get("semantic_time_grain"):
        override["time_grain"] = meta["semantic_time_grain"].strip()
    if meta.get("semantic_metric_roles"):
        override["metric_roles"] = _parse_dict_text(meta["semantic_metric_roles"])
    if meta.get("semantic_field_roles"):
        override["field_roles"] = _parse_dict_text(meta["semantic_field_roles"])
    if meta.get("semantic_derived_metrics"):
        override["derived_metrics"] = _parse_derived_metrics(meta["semantic_derived_metrics"])

    return override


def normalize_id(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_\-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "query"


def parse_markdown_sql(text: str) -> List[Dict]:
    lines = text.splitlines()
    section_stack: List[str] = []
    pending_meta: Dict[str, str] = {}
    queries: List[Dict] = []

    in_sql = False
    sql_lines: List[str] = []
    block_meta: Dict[str, str] = {}

    for line in lines:
        heading_match = HEADING_RE.match(line)
        if not in_sql and heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            section_stack = section_stack[: level - 1]
            section_stack.append(title)
            continue

        if not in_sql:
            meta_match = META_RE.match(line)
            if meta_match:
                key = meta_match.group(1).strip().lower()
                value = meta_match.group(2).strip()
                pending_meta[key] = value
                continue

            if SQL_FENCE_START_RE.match(line):
                in_sql = True
                sql_lines = []
                block_meta = dict(pending_meta)
                pending_meta = {}
                continue

            # Reset metadata on non-empty non-meta non-fence line to avoid leakage.
            if line.strip():
                pending_meta = {}
            continue

        # in_sql mode
        if FENCE_END_RE.match(line):
            sql_text = "\n".join(sql_lines).strip()
            if sql_text:
                idx = len(queries) + 1
                section_title = " / ".join(section_stack) if section_stack else "Untitled"
                default_id = f"q_{idx:03d}"
                qid = normalize_id(block_meta.get("id", default_id))

                filters_raw = block_meta.get("filters", "")
                filters = [v.strip() for v in filters_raw.split(",") if v.strip()]

                query = {
                    "id": qid,
                    "index": idx,
                    "title": block_meta.get("title", section_title),
                    "section": section_title,
                    "datasource": block_meta.get("datasource", ""),
                    "refresh": block_meta.get("refresh", ""),
                    "chart_hint": block_meta.get("chart", "auto").strip().lower(),
                    "filters": filters,
                    "sql": sql_text,
                }
                semantic_override = parse_semantic_override(block_meta)
                if semantic_override:
                    query["semantic_override"] = semantic_override
                extra_meta = {k: v for k, v in block_meta.items() if k not in KNOWN_META_KEYS and not k.startswith("semantic_")}
                if extra_meta:
                    query["extra_meta"] = extra_meta
                queries.append(query)

            in_sql = False
            sql_lines = []
            block_meta = {}
            continue

        sql_lines.append(line)

    return queries


def build_output(queries: List[Dict], source: Path) -> Dict:
    return {
        "source": str(source),
        "query_count": len(queries),
        "queries": queries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse sql.md into query_catalog.json")
    parser.add_argument("--input", required=True, help="Path to sql markdown file")
    parser.add_argument("--output", required=True, help="Path to output query_catalog.json")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    text = in_path.read_text(encoding="utf-8")
    queries = parse_markdown_sql(text)
    result = build_output(queries, in_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Parsed {len(queries)} SQL blocks -> {out_path}")


if __name__ == "__main__":
    main()
