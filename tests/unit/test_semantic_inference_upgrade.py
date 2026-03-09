from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PARSE_SQL_MD_PATH = REPO_ROOT / "skills" / "sql-to-bi-builder" / "scripts" / "parse_sql_md.py"
INFER_SEMANTICS_PATH = REPO_ROOT / "skills" / "sql-to-bi-builder" / "scripts" / "infer_semantics.py"


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SemanticInferenceUpgradeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parse_sql_md = _load_module(PARSE_SQL_MD_PATH, "parse_sql_md_mod")
        cls.infer_semantics = _load_module(INFER_SEMANTICS_PATH, "infer_semantics_mod")

    def _infer(self, sql: str, query_id: str = "q_test", override: dict | None = None) -> dict:
        query = {"id": query_id, "title": query_id, "sql": sql}
        if override:
            query["semantic_override"] = override
        return self.infer_semantics.infer_query_semantics(query)

    def test_time_grain_and_metric_roles(self) -> None:
        sem = self._infer(
            """
            SELECT
              DATE_TRUNC('month', pay_time) AS month_start,
              SUM(amount) AS gmv,
              COUNT(DISTINCT user_id) AS buyer_cnt
            FROM orders
            GROUP BY 1
            """
        )
        self.assertEqual(sem["time_grain"], "month")
        self.assertEqual(sem["grain_hint"], "time_series:month")

        fields = {f["name"]: f for f in sem["fields"]}
        self.assertEqual(fields["gmv"]["role"], "metric")
        self.assertEqual(fields["gmv"]["metric_role"], "sum")
        self.assertEqual(fields["buyer_cnt"]["metric_role"], "count_distinct")

    def test_derived_metrics_inference(self) -> None:
        sem = self._infer(
            """
            SELECT
              DATE(pay_time) AS dt,
              SUM(amount) AS gmv,
              SUM(amount) AS gmv_yoy
            FROM orders
            GROUP BY 1
            """
        )
        derived = {d["name"]: d for d in sem["derived_metrics"]}
        self.assertIn("gmv_yoy", derived)
        self.assertEqual(derived["gmv_yoy"]["type"], "yoy")
        self.assertEqual(derived["gmv_yoy"]["base_metric"], "gmv")
        self.assertEqual(derived["gmv_yoy"]["source"], "inferred")

    def test_override_from_semantic_override_json(self) -> None:
        md = """
        # Demo

        ## card: override-json
        - id: override_json
        - semantic_override: {"grain":"month","time_field":"biz_date","metric_roles":{"gmv":"sum"},"derived_metrics":[{"name":"gmv_mom","type":"mom","base_metric":"gmv"}]}

        ```sql
        SELECT biz_date, amount AS gmv
        FROM orders
        ```
        """
        queries = self.parse_sql_md.parse_markdown_sql(md)
        self.assertEqual(len(queries), 1)
        sem = self.infer_semantics.infer_query_semantics(queries[0])

        fields = {f["name"]: f for f in sem["fields"]}
        self.assertEqual(fields["biz_date"]["role"], "time")
        self.assertEqual(fields["gmv"]["role"], "metric")
        self.assertEqual(fields["gmv"]["metric_role"], "sum")
        self.assertEqual(fields["gmv"]["metric_role_source"], "override")
        self.assertEqual(sem["time_grain"], "month")
        self.assertEqual(sem["time_grain_source"], "override")

        derived = {d["name"]: d for d in sem["derived_metrics"]}
        self.assertIn("gmv_mom", derived)
        self.assertEqual(derived["gmv_mom"]["type"], "mom")
        self.assertEqual(derived["gmv_mom"]["source"], "override")

    def test_override_from_semantic_shorthand_meta(self) -> None:
        md = """
        # Demo

        ## card: override-short
        - id: override_short
        - semantic_grain: week
        - semantic_time_field: week_start
        - semantic_metric_roles: order_cnt:count
        - semantic_derived_metrics: order_cnt_ytd:ytd:order_cnt

        ```sql
        SELECT week_start, COUNT(*) AS order_cnt, COUNT(*) AS order_cnt_ytd
        FROM orders
        GROUP BY 1
        ```
        """
        queries = self.parse_sql_md.parse_markdown_sql(md)
        self.assertEqual(len(queries), 1)
        sem = self.infer_semantics.infer_query_semantics(queries[0])

        self.assertEqual(sem["time_grain"], "week")
        self.assertEqual(sem["time_grain_source"], "override")
        fields = {f["name"]: f for f in sem["fields"]}
        self.assertEqual(fields["order_cnt"]["metric_role"], "count")
        self.assertEqual(fields["order_cnt"]["metric_role_source"], "override")
        derived = {d["name"]: d for d in sem["derived_metrics"]}
        self.assertEqual(derived["order_cnt_ytd"]["type"], "ytd")
        self.assertEqual(derived["order_cnt_ytd"]["source"], "override")

    def test_baseline_accuracy_sample(self) -> None:
        cases = [
            {
                "sql": "SELECT DATE(pay_time) AS dt, SUM(amount) AS gmv FROM orders GROUP BY 1",
                "time_grain": "day",
                "metric_roles": {"gmv": "sum"},
            },
            {
                "sql": "SELECT DATE_TRUNC('week', pay_time) AS week_start, COUNT(*) AS order_cnt FROM orders GROUP BY 1",
                "time_grain": "week",
                "metric_roles": {"order_cnt": "count"},
            },
            {
                "sql": "SELECT DATE_TRUNC('month', pay_time) AS month_start, AVG(amount) AS avg_order_amount FROM orders GROUP BY 1",
                "time_grain": "month",
                "metric_roles": {"avg_order_amount": "avg"},
            },
            {
                "sql": "SELECT DATE_TRUNC('year', pay_time) AS year_start, COUNT(DISTINCT user_id) AS buyer_cnt FROM orders GROUP BY 1",
                "time_grain": "year",
                "metric_roles": {"buyer_cnt": "count_distinct"},
            },
            {
                "sql": "SELECT DATE(pay_time) AS dt, SUM(amount) AS gmv, SUM(amount) AS gmv_mom FROM orders GROUP BY 1",
                "time_grain": "day",
                "metric_roles": {"gmv": "sum", "gmv_mom": "sum"},
                "derived": {"gmv_mom": "mom"},
            },
        ]

        checks = 0
        hits = 0
        for idx, case in enumerate(cases, start=1):
            sem = self._infer(case["sql"], query_id=f"baseline_{idx}")
            checks += 1
            if sem.get("time_grain") == case["time_grain"]:
                hits += 1

            field_map = {f["name"]: f for f in sem["fields"]}
            for metric_name, expected_role in case["metric_roles"].items():
                checks += 1
                if field_map.get(metric_name, {}).get("metric_role") == expected_role:
                    hits += 1

            derived_expect = case.get("derived", {})
            if derived_expect:
                derived_map = {d["name"]: d for d in sem["derived_metrics"]}
                for metric_name, expected_type in derived_expect.items():
                    checks += 1
                    if derived_map.get(metric_name, {}).get("type") == expected_type:
                        hits += 1

        accuracy = hits / checks if checks else 0.0
        self.assertGreaterEqual(accuracy, 0.9, f"baseline sample accuracy too low: {hits}/{checks}={accuracy:.2%}")


if __name__ == "__main__":
    unittest.main()
