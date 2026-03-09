#!/usr/bin/env python3.11
"""Infer metric/dimension/time semantics from query catalog."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

AGG_RE = re.compile(r"\b(sum|count|avg|min|max)\s*\(", re.IGNORECASE)
COUNT_DISTINCT_RE = re.compile(r"\bcount\s*\(\s*distinct\b", re.IGNORECASE)
TIME_NAME_RE = re.compile(r"\b(date|dt|day|week|month|year|time|hour)\b", re.IGNORECASE)
TIME_FIELD_RE = re.compile(
    r"(^|_)(dt|date|day|week|month|year|time|hour|minute|second|timestamp|ts|at)$",
    re.IGNORECASE,
)
TIME_BUCKET_FUNC_RE = re.compile(
    r"\bdate_trunc\s*\(\s*['\"](?P<grain>day|week|month|quarter|year)['\"]",
    re.IGNORECASE,
)
EXTRACT_GRAIN_RE = re.compile(
    r"\bextract\s*\(\s*(?P<grain>day|week|month|quarter|year)\s+from",
    re.IGNORECASE,
)
DATE_FUNC_DAY_RE = re.compile(r"\bdate\s*\(", re.IGNORECASE)
MONTH_FORMAT_RE = re.compile(r"%(?:Y-)?m|yyyy-?mm", re.IGNORECASE)
YEAR_FORMAT_RE = re.compile(r"%Y|yyyy", re.IGNORECASE)
DERIVED_YOY_RE = re.compile(r"(^|[^a-z0-9])(yoy|year[_\s]?over[_\s]?year)([^a-z0-9]|$)", re.IGNORECASE)
DERIVED_MOM_RE = re.compile(r"(^|[^a-z0-9])(mom|month[_\s]?over[_\s]?month)([^a-z0-9]|$)", re.IGNORECASE)
DERIVED_YTD_RE = re.compile(r"(^|[^a-z0-9])(ytd|year[_\s]?to[_\s]?date)([^a-z0-9]|$)", re.IGNORECASE)
METRIC_NAME_RE = re.compile(
    r"\b(gmv|revenue|sales|amount|amt|count|cnt|total|rate|ratio|pct|percent|orders|users)\b",
    re.IGNORECASE,
)
ARITHMETIC_RE = re.compile(r"[+\-*/]")
WHERE_RE = re.compile(
    r"\bwhere\b(?P<body>.*?)(\bgroup\s+by\b|\border\s+by\b|\bhaving\b|\blimit\b|\bunion\b|$)",
    re.IGNORECASE | re.DOTALL,
)
IDENT_OR_FUNC = r"(?:[a-zA-Z_][\w$]*(?:\.[a-zA-Z_][\w$]*)*|`[^`]+`|\"[^\"]+\"|\[[^\]]+\]|[a-zA-Z_][\w$]*\s*\([^()]*\))"
BETWEEN_PRED_RE = re.compile(
    rf"^\s*(?P<expr>{IDENT_OR_FUNC})\s+between\s+(?P<left>.+?)\s+and\s+(?P<right>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)
IN_PRED_RE = re.compile(
    rf"^\s*(?P<expr>{IDENT_OR_FUNC})\s+(?P<op>in|not\s+in)\s*\((?P<vals>.*)\)\s*$",
    re.IGNORECASE | re.DOTALL,
)
IS_NULL_PRED_RE = re.compile(
    rf"^\s*(?P<expr>{IDENT_OR_FUNC})\s+is\s+(?P<op>not\s+null|null)\s*$",
    re.IGNORECASE | re.DOTALL,
)
CMP_PRED_RE = re.compile(
    rf"^\s*(?P<expr>{IDENT_OR_FUNC})\s*(?P<op>>=|<=|<>|!=|=|>|<|like|ilike)\s*(?P<val>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)
BETWEEN_SCAN_RE = re.compile(
    rf"(?P<expr>{IDENT_OR_FUNC})\s+between\s+(?P<left>.+?)\s+and\s+(?P<right>.+?)(?=(\s+and\s+|\s+or\s+|$))",
    re.IGNORECASE | re.DOTALL,
)
IN_SCAN_RE = re.compile(
    rf"(?P<expr>{IDENT_OR_FUNC})\s+(?P<op>in|not\s+in)\s*\((?P<vals>[^)]*)\)",
    re.IGNORECASE | re.DOTALL,
)
CMP_SCAN_RE = re.compile(
    rf"(?P<expr>{IDENT_OR_FUNC})\s*(?P<op>>=|<=|<>|!=|=|>|<|like|ilike)\s*(?P<val>(?:'[^']*'|\"[^\"]*\"|\{{\{{[^}}]+\}}\}}|:[a-zA-Z_][a-zA-Z0-9_]*|\$[a-zA-Z_][a-zA-Z0-9_]*|\?|[0-9]+(?:\.[0-9]+)?|[a-zA-Z_][a-zA-Z0-9_\.]*))",
    re.IGNORECASE | re.DOTALL,
)
PLACEHOLDER_RE = re.compile(r"(\{\{[^}]+\}\}|:[a-zA-Z_][a-zA-Z0-9_]*|\$[a-zA-Z_][a-zA-Z0-9_]*|\?)")
NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
INT_RE = re.compile(r"^-?\d+$")
DATE_FUNCTION_RE = re.compile(
    r"^(date|to_date|str_to_date|date_trunc|timestamp|to_timestamp)\s*\(|^cast\s*\(.*\s+as\s+(date|timestamp).*$",
    re.IGNORECASE,
)

DATE_STRING_FORMATS = [
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "yyyy-mm-dd"),
    (re.compile(r"^\d{4}/\d{2}/\d{2}$"), "yyyy/mm/dd"),
    (re.compile(r"^\d{8}$"), "yyyymmdd"),
    (re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}$"), "yyyy-mm-dd hh:mm:ss"),
    (
        re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+\-]\d{2}:?\d{2})?$"),
        "iso-8601",
    ),
]


def extract_select_clause(sql: str) -> str:
    normalized = " ".join(sql.strip().split())
    lower = normalized.lower()
    s_idx = lower.find("select ")
    if s_idx < 0:
        return ""
    f_idx = lower.find(" from ", s_idx)
    if f_idx < 0:
        return normalized[s_idx + 7 :]
    return normalized[s_idx + 7 : f_idx]


def split_select_items(select_clause: str) -> List[str]:
    items: List[str] = []
    buf: List[str] = []
    depth = 0
    for ch in select_clause:
        if ch == "(":
            depth += 1
        elif ch == ")" and depth > 0:
            depth -= 1
        if ch == "," and depth == 0:
            item = "".join(buf).strip()
            if item:
                items.append(item)
            buf = []
            continue
        buf.append(ch)
    final = "".join(buf).strip()
    if final:
        items.append(final)
    return items


def extract_alias(expr: str, idx: int) -> str:
    m = re.search(r"\s+as\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*$", expr, re.IGNORECASE)
    if m:
        return m.group(1)

    tail = expr.strip().split()
    if len(tail) > 1 and re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", tail[-1]):
        return tail[-1]

    cleaned = expr.strip()
    if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_\.]*", cleaned):
        return cleaned.split(".")[-1]

    return f"col_{idx:02d}"


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower()).strip("_")


def parse_mapping(raw: Any) -> Dict[str, str]:
    if isinstance(raw, dict):
        return {normalize_name(str(k)): str(v).strip().lower() for k, v in raw.items() if str(k).strip()}
    if isinstance(raw, str):
        out: Dict[str, str] = {}
        for piece in re.split(r"[;,]", raw):
            token = piece.strip()
            if not token:
                continue
            if ":" in token:
                key, value = token.split(":", 1)
            elif "=" in token:
                key, value = token.split("=", 1)
            else:
                continue
            key_name = normalize_name(key)
            if key_name:
                out[key_name] = value.strip().lower()
        return out
    return {}


def parse_semantic_override(query: Dict) -> Dict[str, Any]:
    raw = query.get("semantic_override")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def detect_metric_role(alias: str, expr: str) -> Tuple[Optional[str], str, float]:
    text = " ".join(expr.strip().lower().split())
    alias_l = alias.lower()

    if COUNT_DISTINCT_RE.search(text):
        return "count_distinct", "detected count(distinct ...)", 0.99
    if re.search(r"\bsum\s*\(", text):
        return "sum", "detected sum(...)", 0.98
    if re.search(r"\bavg\s*\(", text):
        return "avg", "detected avg(...)", 0.98
    if re.search(r"\bcount\s*\(", text):
        return "count", "detected count(...)", 0.98
    if re.search(r"\bmin\s*\(", text):
        return "min", "detected min(...)", 0.96
    if re.search(r"\bmax\s*\(", text):
        return "max", "detected max(...)", 0.96
    if AGG_RE.search(text) and "/" in text:
        return "ratio", "detected aggregate ratio expression", 0.88
    if ARITHMETIC_RE.search(text) and METRIC_NAME_RE.search(alias_l):
        return "unknown", "metric-like alias with arithmetic expression", 0.7
    if METRIC_NAME_RE.search(alias_l) and AGG_RE.search(text):
        return "unknown", "metric-like alias with aggregate expression", 0.68
    return None, "no strong metric signal", 0.55


def detect_time_grain(alias: str, expr: str) -> Tuple[str, str, float]:
    text = " ".join(expr.strip().lower().split())
    alias_l = alias.lower()

    m = TIME_BUCKET_FUNC_RE.search(text)
    if m:
        grain = m.group("grain").lower()
        return grain, f"detected date_trunc('{grain}', ...)", 0.99

    m = EXTRACT_GRAIN_RE.search(text)
    if m:
        grain = m.group("grain").lower()
        return grain, f"detected extract({grain} from ...)", 0.95

    if DATE_FUNC_DAY_RE.search(text):
        return "day", "detected date(...) bucketing", 0.92

    if re.search(r"(^|_)(week|wk|week_start)($|_)", alias_l):
        return "week", "time alias suggests week grain", 0.9
    if re.search(r"(^|_)(month|mon|month_start)($|_)", alias_l):
        return "month", "time alias suggests month grain", 0.9
    if re.search(r"(^|_)(quarter|qtr)($|_)", alias_l):
        return "quarter", "time alias suggests quarter grain", 0.9
    if re.search(r"(^|_)(year|yr)($|_)", alias_l):
        return "year", "time alias suggests year grain", 0.9
    if re.search(r"(^|_)(dt|date|day)($|_)", alias_l):
        return "day", "time alias suggests day grain", 0.86

    if MONTH_FORMAT_RE.search(text):
        return "month", "detected month date format pattern", 0.8
    if YEAR_FORMAT_RE.search(text):
        return "year", "detected year date format pattern", 0.76

    return "unknown", "unable to infer specific time grain", 0.4


def detect_role(alias: str, expr: str, metric_role: Optional[str]) -> Tuple[str, str, float]:
    if metric_role is not None:
        return "metric", f"metric role={metric_role}", 0.95

    if TIME_NAME_RE.search(alias) or TIME_NAME_RE.search(expr):
        return "time", "time name pattern matched", 0.9

    return "dimension", "fallback dimension classification", 0.62


def detect_grain(fields: List[Dict]) -> str:
    has_time = any(f["role"] == "time" for f in fields)
    dim_count = sum(1 for f in fields if f["role"] in {"dimension", "time"})
    metric_count = sum(1 for f in fields if f["role"] == "metric")

    if has_time and metric_count:
        return "time_series"
    if dim_count == 0 and metric_count:
        return "single_value"
    if dim_count >= 1 and metric_count:
        return "categorical"
    return "detail"


def normalize_grain(value: Any) -> str:
    grain = str(value or "").strip().lower()
    if grain in {"day", "week", "month", "quarter", "year"}:
        return grain
    return "unknown"


def infer_query_time_grain(fields: List[Dict]) -> Tuple[str, str]:
    counts: Dict[str, int] = {}
    for field in fields:
        if field.get("role") != "time":
            continue
        grain = normalize_grain(field.get("time_grain"))
        if grain == "unknown":
            continue
        counts[grain] = counts.get(grain, 0) + 1

    if not counts:
        return "unknown", "no time grain signal"

    rank = {"day": 1, "week": 2, "month": 3, "quarter": 4, "year": 5}
    chosen = sorted(counts.items(), key=lambda kv: (-kv[1], rank.get(kv[0], 999)))[0][0]
    return chosen, "derived from time fields"


def infer_derived_type(alias: str, expr: str) -> Tuple[Optional[str], str]:
    text = " ".join(expr.strip().lower().split())
    alias_l = alias.lower()

    if DERIVED_YOY_RE.search(alias_l) or DERIVED_YOY_RE.search(text):
        return "yoy", "detected yoy pattern in alias/expression"
    if DERIVED_MOM_RE.search(alias_l) or DERIVED_MOM_RE.search(text):
        return "mom", "detected mom pattern in alias/expression"
    if DERIVED_YTD_RE.search(alias_l) or DERIVED_YTD_RE.search(text):
        return "ytd", "detected ytd pattern in alias/expression"
    return None, "no derived metric pattern"


def guess_base_metric(name: str, dtype: str) -> Optional[str]:
    alias = normalize_name(name)
    suffix = f"_{dtype}"
    prefix = f"{dtype}_"

    if alias.endswith(suffix):
        base = alias[: -len(suffix)].strip("_")
        return base or None
    if alias.startswith(prefix):
        base = alias[len(prefix) :].strip("_")
        return base or None
    return None


def infer_derived_metrics(fields: List[Dict]) -> List[Dict]:
    out: List[Dict] = []
    for field in fields:
        if field.get("role") != "metric":
            continue
        dtype, reason = infer_derived_type(str(field.get("name", "")), str(field.get("expression", "")))
        if not dtype:
            continue
        out.append(
            {
                "name": field.get("name"),
                "type": dtype,
                "base_metric": guess_base_metric(str(field.get("name", "")), dtype),
                "expression": field.get("expression", ""),
                "source": "inferred",
                "reason": reason,
            }
        )
    return out


def normalize_derived_overrides(raw: Any) -> List[Dict]:
    if not isinstance(raw, list):
        return []

    out: List[Dict] = []
    for item in raw:
        if isinstance(item, str):
            out.append({"name": item, "type": item, "source": "override", "reason": "manual override"})
            continue
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        dtype = str(item.get("type", "")).strip().lower()
        if not name or not dtype:
            continue
        out.append(
            {
                "name": name,
                "type": dtype,
                "base_metric": item.get("base_metric"),
                "expression": item.get("expression", ""),
                "source": "override",
                "reason": "manual override",
            }
        )
    return out


def merge_derived_metrics(inferred: List[Dict], overrides: List[Dict]) -> List[Dict]:
    merged: Dict[str, Dict] = {}
    for item in inferred:
        key = normalize_name(str(item.get("name", "")))
        if key:
            merged[key] = item
    for item in overrides:
        key = normalize_name(str(item.get("name", "")))
        if key:
            merged[key] = item
    return list(merged.values())


def apply_semantic_overrides(fields: List[Dict], override: Dict[str, Any]) -> None:
    if not override:
        return

    field_roles = parse_mapping(override.get("field_roles"))
    metric_roles = parse_mapping(override.get("metric_roles"))

    raw_time_field = override.get("time_field")
    time_fields_override = set()
    if isinstance(raw_time_field, str) and raw_time_field.strip():
        time_fields_override.add(normalize_name(raw_time_field))
    elif isinstance(raw_time_field, list):
        time_fields_override = {normalize_name(str(v)) for v in raw_time_field if str(v).strip()}

    for field in fields:
        name_key = normalize_name(str(field.get("name", "")))
        source_key = normalize_name(str(field.get("source_name", "")))

        role_override = field_roles.get(name_key) or field_roles.get(source_key)
        if role_override:
            field["role"] = role_override
            field["role_source"] = "override"
            field["role_reason"] = "manual field role override"
            field["role_confidence"] = 1.0

        if name_key in time_fields_override or source_key in time_fields_override:
            field["role"] = "time"
            field["role_source"] = "override"
            field["role_reason"] = "manual time_field override"
            field["role_confidence"] = 1.0
            if normalize_grain(override.get("grain")) != "unknown":
                field["time_grain"] = normalize_grain(override.get("grain"))
                field["time_grain_source"] = "override"
                field["time_grain_reason"] = "manual grain override"

        metric_override = metric_roles.get(name_key) or metric_roles.get(source_key)
        if metric_override:
            field["role"] = "metric"
            field["metric_role"] = metric_override
            field["metric_role_source"] = "override"
            field["metric_role_reason"] = "manual metric role override"
            field["role_source"] = "override"
            field["role_reason"] = "manual metric role override"
            field["role_confidence"] = 1.0

def to_field_name(expr: str) -> str:
    cleaned = expr.strip().strip("()")
    ident_list = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", cleaned)
    if not ident_list:
        return cleaned.lower()
    return ident_list[-1].lower()


def is_time_field(expr: str, field: str) -> bool:
    return bool(TIME_NAME_RE.search(expr) or TIME_NAME_RE.search(field) or TIME_FIELD_RE.search(field))


def normalize_operator(op: str) -> str:
    return " ".join(op.strip().lower().split())


def extract_where_clause(sql: str) -> str:
    normalized = " ".join(sql.strip().split())
    m = WHERE_RE.search(normalized)
    if not m:
        return ""
    return m.group("body").strip()


def has_outer_parentheses(expr: str) -> bool:
    expr = expr.strip()
    if len(expr) < 2 or expr[0] != "(" or expr[-1] != ")":
        return False

    depth = 0
    quote: Optional[str] = None
    for i, ch in enumerate(expr):
        if quote:
            if ch == quote and (i == 0 or expr[i - 1] != "\\"):
                quote = None
            continue
        if ch in {"'", '"', "`"}:
            quote = ch
            continue
        if ch == "(":
            depth += 1
            continue
        if ch == ")":
            depth -= 1
            if depth == 0 and i < len(expr) - 1:
                return False
            continue

    return depth == 0 and quote is None


def strip_outer_parentheses(expr: str) -> str:
    out = expr.strip()
    while has_outer_parentheses(out):
        out = out[1:-1].strip()
    return out


def split_top_level_boolean(expr: str, keyword: str) -> List[str]:
    keyword = keyword.lower()
    lower = expr.lower()

    parts: List[str] = []
    last = 0
    i = 0
    depth = 0
    quote: Optional[str] = None
    between_pending = False

    while i < len(expr):
        ch = expr[i]

        if quote:
            if ch == quote and (i == 0 or expr[i - 1] != "\\"):
                quote = None
            i += 1
            continue

        if ch in {"'", '"', "`"}:
            quote = ch
            i += 1
            continue

        if ch == "(":
            depth += 1
            i += 1
            continue

        if ch == ")":
            depth = max(0, depth - 1)
            i += 1
            continue

        if depth == 0 and (ch.isalpha() or ch == "_"):
            start = i
            i += 1
            while i < len(expr) and (expr[i].isalnum() or expr[i] == "_"):
                i += 1
            token = lower[start:i]

            if token == "between":
                between_pending = True
                continue

            if token == "and" and between_pending:
                between_pending = False
                continue

            if token == keyword and not between_pending:
                part = expr[last:start].strip()
                if part:
                    parts.append(part)
                last = i
                continue

            continue

        i += 1

    tail = expr[last:].strip()
    if tail:
        parts.append(tail)

    return parts


def build_boolean_ast(expr: str) -> Dict:
    expr = strip_outer_parentheses(expr)
    if not expr:
        return {"type": "empty"}

    or_parts = split_top_level_boolean(expr, "or")
    if len(or_parts) > 1:
        return {"type": "or", "children": [build_boolean_ast(p) for p in or_parts]}

    and_parts = split_top_level_boolean(expr, "and")
    if len(and_parts) > 1:
        return {"type": "and", "children": [build_boolean_ast(p) for p in and_parts]}

    return {"type": "predicate", "text": strip_outer_parentheses(expr)}


def iter_predicates(ast: Dict) -> Iterator[str]:
    node_type = ast.get("type")
    if node_type == "predicate":
        text = ast.get("text", "").strip()
        if text:
            yield text
        return
    for child in ast.get("children", []):
        yield from iter_predicates(child)


def split_csv_top_level(text: str) -> List[str]:
    items: List[str] = []
    buf: List[str] = []
    depth = 0
    quote: Optional[str] = None

    for i, ch in enumerate(text):
        if quote:
            buf.append(ch)
            if ch == quote and (i == 0 or text[i - 1] != "\\"):
                quote = None
            continue

        if ch in {"'", '"', "`"}:
            quote = ch
            buf.append(ch)
            continue

        if ch == "(":
            depth += 1
            buf.append(ch)
            continue

        if ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
            continue

        if ch == "," and depth == 0:
            item = "".join(buf).strip()
            if item:
                items.append(item)
            buf = []
            continue

        buf.append(ch)

    final = "".join(buf).strip()
    if final:
        items.append(final)
    return items


def parse_int_date_format(text: str) -> Optional[str]:
    if not re.fullmatch(r"\d+", text):
        return None

    if len(text) == 8:
        try:
            datetime.strptime(text, "%Y%m%d")
            return "yyyymmdd_int"
        except ValueError:
            return None

    if len(text) == 10:
        value = int(text)
        if 946684800 <= value <= 4102444800:
            return "unix_seconds_int"

    if len(text) == 13:
        value = int(text)
        if 946684800000 <= value <= 4102444800000:
            return "unix_milliseconds_int"

    return None


def parse_date_string_format(text: str) -> Optional[str]:
    for pattern, fmt in DATE_STRING_FORMATS:
        if pattern.fullmatch(text):
            # Validate yyyymmdd string to avoid 20249999 false positives.
            if fmt == "yyyymmdd":
                try:
                    datetime.strptime(text, "%Y%m%d")
                except ValueError:
                    return None
            return fmt
    return None


def parse_value_info(raw_value: str) -> Dict:
    value = raw_value.strip().rstrip(";").strip()

    if PLACEHOLDER_RE.search(value):
        return {
            "mode": "parameterized",
            "type": "parameter",
            "format": None,
            "is_date": False,
            "sample": value[:80],
        }

    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        inner = value[1:-1].strip()
        date_fmt = parse_date_string_format(inner)
        if date_fmt:
            return {
                "mode": "literal",
                "type": "date",
                "format": date_fmt,
                "is_date": True,
                "sample": value[:80],
            }
        int_date_fmt = parse_int_date_format(inner)
        if int_date_fmt:
            return {
                "mode": "literal",
                "type": "date",
                "format": int_date_fmt,
                "is_date": True,
                "sample": value[:80],
            }
        return {
            "mode": "literal",
            "type": "string",
            "format": None,
            "is_date": False,
            "sample": value[:80],
        }

    if DATE_FUNCTION_RE.search(value):
        return {
            "mode": "literal",
            "type": "date",
            "format": "date_function",
            "is_date": True,
            "sample": value[:80],
        }

    if INT_RE.fullmatch(value):
        int_date_fmt = parse_int_date_format(value)
        if int_date_fmt:
            return {
                "mode": "literal",
                "type": "date",
                "format": int_date_fmt,
                "is_date": True,
                "sample": value[:80],
            }
        return {
            "mode": "literal",
            "type": "number",
            "format": "integer",
            "is_date": False,
            "sample": value[:80],
        }

    if NUMBER_RE.fullmatch(value):
        return {
            "mode": "literal",
            "type": "number",
            "format": "float",
            "is_date": False,
            "sample": value[:80],
        }

    date_fmt = parse_date_string_format(value)
    if date_fmt:
        return {
            "mode": "literal",
            "type": "date",
            "format": date_fmt,
            "is_date": True,
            "sample": value[:80],
        }

    if value.lower() in {"current_date", "current_timestamp", "now()"}:
        return {
            "mode": "literal",
            "type": "date",
            "format": "date_keyword",
            "is_date": True,
            "sample": value[:80],
        }

    if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_\.]*", value):
        return {
            "mode": "literal",
            "type": "identifier",
            "format": None,
            "is_date": False,
            "sample": value[:80],
        }

    return {
        "mode": "literal",
        "type": "unknown",
        "format": None,
        "is_date": False,
        "sample": value[:80],
    }


def summarize_value_infos(operator: str, value_infos: List[Dict]) -> Dict:
    op = normalize_operator(operator)

    modes = {v["mode"] for v in value_infos}
    types = {v["type"] for v in value_infos}
    formats = [v["format"] for v in value_infos if v.get("format")]
    all_date = all(v["is_date"] for v in value_infos if v["mode"] == "literal") and any(v["is_date"] for v in value_infos)
    any_date = any(v["is_date"] for v in value_infos)
    all_number = all(v["type"] == "number" for v in value_infos if v["mode"] == "literal") and any(
        v["type"] == "number" for v in value_infos
    )

    mode = "parameterized" if "parameterized" in modes else "literal"

    if op == "between":
        if any_date:
            value_type = "date_range"
        elif all_number:
            value_type = "number_range"
        else:
            value_type = "range"
    elif op in {"in", "not in"}:
        if all_date:
            value_type = "date_set"
        elif all_number:
            value_type = "number_set"
        elif types == {"string"}:
            value_type = "string_set"
        else:
            value_type = "set"
    else:
        value_type = value_infos[0]["type"] if value_infos else "unknown"

    value_format = None
    if formats:
        unique_formats = sorted(set(formats))
        value_format = unique_formats[0] if len(unique_formats) == 1 else "mixed"

    return {
        "value_mode": mode,
        "value_type": value_type,
        "value_format": value_format,
        "is_date_value": any_date,
    }


def infer_filter_widget(operator: str, is_time: bool, value_type: str) -> str:
    op = normalize_operator(operator)
    if op == "between":
        return "date_range" if is_time or value_type == "date_range" else "number_range"
    if op in {"in", "not in"}:
        return "multi_select"
    if op in {"like", "ilike"}:
        return "search"
    if op in {"is null", "is not null"}:
        return "select"
    if is_time:
        return "date_select"
    if value_type in {"number", "number_set", "number_range"}:
        return "number_input"
    return "select"


def parse_predicate(predicate: str, parse_mode: str) -> Optional[Dict]:
    text = strip_outer_parentheses(predicate.strip())
    if not text:
        return None

    m = BETWEEN_PRED_RE.match(text)
    if m:
        expr = m.group("expr").strip()
        left = parse_value_info(m.group("left"))
        right = parse_value_info(m.group("right"))
        summary = summarize_value_infos("between", [left, right])
        field = to_field_name(expr)
        time_field = is_time_field(expr, field) or summary["is_date_value"]
        value_type = summary["value_type"]
        if time_field and value_type == "range":
            value_type = "date_range"
        return {
            "field": field,
            "expression": expr,
            "operator": "between",
            "value_mode": summary["value_mode"],
            "value_type": value_type,
            "value_format": summary["value_format"],
            "value_sample": f"{left['sample']} and {right['sample']}"[:80],
            "suggested_widget": infer_filter_widget("between", time_field, value_type),
            "is_time": time_field,
            "source_clause": "where",
            "parse_mode": parse_mode,
        }

    m = IN_PRED_RE.match(text)
    if m:
        expr = m.group("expr").strip()
        op = normalize_operator(m.group("op"))
        values = split_csv_top_level(m.group("vals"))
        infos = [parse_value_info(v) for v in values if v.strip()]
        if not infos:
            infos = [parse_value_info(m.group("vals"))]
        summary = summarize_value_infos(op, infos)
        field = to_field_name(expr)
        time_field = is_time_field(expr, field) or summary["is_date_value"]
        return {
            "field": field,
            "expression": expr,
            "operator": op,
            "value_mode": summary["value_mode"],
            "value_type": summary["value_type"],
            "value_format": summary["value_format"],
            "value_sample": ", ".join(v["sample"] for v in infos)[:80],
            "suggested_widget": infer_filter_widget(op, time_field, summary["value_type"]),
            "is_time": time_field,
            "source_clause": "where",
            "parse_mode": parse_mode,
        }

    m = IS_NULL_PRED_RE.match(text)
    if m:
        expr = m.group("expr").strip()
        op = normalize_operator(f"is {m.group('op')}")
        field = to_field_name(expr)
        time_field = is_time_field(expr, field)
        return {
            "field": field,
            "expression": expr,
            "operator": op,
            "value_mode": "literal",
            "value_type": "null_check",
            "value_format": None,
            "value_sample": op,
            "suggested_widget": infer_filter_widget(op, time_field, "null_check"),
            "is_time": time_field,
            "source_clause": "where",
            "parse_mode": parse_mode,
        }

    m = CMP_PRED_RE.match(text)
    if m:
        expr = m.group("expr").strip()
        op = normalize_operator(m.group("op"))
        info = parse_value_info(m.group("val"))
        summary = summarize_value_infos(op, [info])
        field = to_field_name(expr)
        time_field = is_time_field(expr, field) or summary["is_date_value"]
        value_type = summary["value_type"]
        if time_field and value_type in {"unknown", "identifier", "parameter"}:
            value_type = "date"
        return {
            "field": field,
            "expression": expr,
            "operator": op,
            "value_mode": summary["value_mode"],
            "value_type": value_type,
            "value_format": summary["value_format"],
            "value_sample": info["sample"][:80],
            "suggested_widget": infer_filter_widget(op, time_field, value_type),
            "is_time": time_field,
            "source_clause": "where",
            "parse_mode": parse_mode,
        }

    return None


def covered_by_span(spans: List[tuple[int, int]], start: int, end: int) -> bool:
    for s, e in spans:
        if start >= s and end <= e:
            return True
    return False


def regex_fallback_filters(where_clause: str) -> List[Dict]:
    candidates: List[Dict] = []
    spans: List[tuple[int, int]] = []

    for pattern in (BETWEEN_SCAN_RE, IN_SCAN_RE, CMP_SCAN_RE):
        for m in pattern.finditer(where_clause):
            start, end = m.span()
            if covered_by_span(spans, start, end):
                continue
            spans.append((start, end))
            parsed = parse_predicate(m.group(0), parse_mode="regex_fallback")
            if parsed:
                candidates.append(parsed)

    return candidates


def dedupe_filters(filters: List[Dict]) -> List[Dict]:
    seen = set()
    out: List[Dict] = []
    for item in filters:
        key = (
            item.get("field"),
            item.get("operator"),
            item.get("value_mode"),
            item.get("value_type"),
            item.get("value_sample"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def extract_dsl_filters(sql: str) -> List[Dict]:
    where_clause = extract_where_clause(sql)
    if not where_clause:
        return []

    ast = build_boolean_ast(where_clause)
    parsed: List[Dict] = []
    for predicate in iter_predicates(ast):
        item = parse_predicate(predicate, parse_mode="dsl_ast")
        if item:
            parsed.append(item)

    if not parsed:
        parsed = regex_fallback_filters(where_clause)

    return dedupe_filters(parsed)


def infer_query_semantics(query: Dict) -> Dict:
    sql = query.get("sql", "")
    select_clause = extract_select_clause(sql)
    items = split_select_items(select_clause)
    override = parse_semantic_override(query)

    fields: List[Dict] = []
    for idx, item in enumerate(items, start=1):
        alias = extract_alias(item, idx)
        metric_role, metric_reason, metric_confidence = detect_metric_role(alias, item)
        role, role_reason, role_confidence = detect_role(alias, item, metric_role)
        time_grain, time_reason, time_confidence = detect_time_grain(alias, item)
        fields.append(
            {
                "name": alias,
                "source_name": to_field_name(item),
                "expression": item,
                "role": role,
                "is_aggregate": bool(AGG_RE.search(item)),
                "role_reason": role_reason,
                "role_confidence": role_confidence,
                "role_source": "inferred",
                "metric_role": metric_role,
                "metric_role_reason": metric_reason,
                "metric_role_confidence": metric_confidence,
                "metric_role_source": "inferred" if metric_role is not None else "n/a",
                "time_grain": time_grain if role == "time" else "unknown",
                "time_grain_reason": time_reason if role == "time" else "",
                "time_grain_confidence": time_confidence if role == "time" else 0.0,
                "time_grain_source": "inferred" if role == "time" else "n/a",
            }
        )

    apply_semantic_overrides(fields, override)

    grain = detect_grain(fields)
    time_grain, time_grain_reason = infer_query_time_grain(fields)
    time_grain_source = "inferred"
    manual_grain = normalize_grain(override.get("time_grain") or override.get("grain"))
    if manual_grain != "unknown":
        time_grain = manual_grain
        time_grain_reason = "manual grain override"
        time_grain_source = "override"

    grain_hint = grain
    if grain == "time_series" and time_grain != "unknown":
        grain_hint = f"time_series:{time_grain}"

    inferred_derived = infer_derived_metrics(fields)
    override_derived = normalize_derived_overrides(override.get("derived_metrics"))
    derived_metrics = merge_derived_metrics(inferred_derived, override_derived)

    dsl_filters = extract_dsl_filters(sql)
    dsl_filter_fields = [f["field"] for f in dsl_filters]

    return {
        "id": query.get("id"),
        "title": query.get("title", ""),
        "grain": grain,
        "grain_hint": grain_hint,
        "time_grain": time_grain,
        "time_grain_reason": time_grain_reason,
        "time_grain_source": time_grain_source,
        "field_count": len(fields),
        "fields": fields,
        "metrics": [f["name"] for f in fields if f["role"] == "metric"],
        "dimensions": [f["name"] for f in fields if f["role"] == "dimension"],
        "time_fields": [f["name"] for f in fields if f["role"] == "time"],
        "derived_metrics": derived_metrics,
        "semantic_override_applied": bool(override),
        "dsl_filters": dsl_filters,
        "dsl_filter_fields": dsl_filter_fields,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Infer semantics from query catalog")
    parser.add_argument("--input", required=True, help="Path to query_catalog.json")
    parser.add_argument("--output", required=True, help="Path to semantic_catalog.json")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    payload = json.loads(in_path.read_text(encoding="utf-8"))
    queries = payload.get("queries", [])

    semantic_queries = [infer_query_semantics(q) for q in queries]

    result = {
        "source": payload.get("source", ""),
        "query_count": len(semantic_queries),
        "queries": semantic_queries,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Inferred semantics for {len(semantic_queries)} queries -> {out_path}")


if __name__ == "__main__":
    main()
